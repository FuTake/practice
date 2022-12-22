package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.GeneratedValue;
import org.neo4j.ogm.annotation.Id;
import org.neo4j.ogm.annotation.NodeEntity;

@Data
public class BaseRelationShip {
    @Id
    @GeneratedValue
    private Long Id;
}
